#!/usr/bin/env python3
"""
Миграция: Добавление UNIQUE constraint для ExternalBusinessReviews
Создает уникальный индекс на (business_id, source, external_review_id)
"""
import sys
import os

# Добавляем путь к src для импорта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from safe_db_utils import get_db_connection, safe_migrate

def migrate():
    """Добавить UNIQUE constraint через уникальный индекс"""
    
    def apply_migration(cursor):
        # Проверяем, существует ли уже такой индекс
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name='idx_ext_reviews_unique'
        """)
        existing_index = cursor.fetchone()
        
        if existing_index:
            print("✅ Уникальный индекс уже существует")
            return
        
        # Проверяем наличие дубликатов перед созданием индекса
        cursor.execute("""
            SELECT business_id, source, external_review_id, COUNT(*) as cnt
            FROM ExternalBusinessReviews
            WHERE external_review_id IS NOT NULL
            GROUP BY business_id, source, external_review_id
            HAVING cnt > 1
        """)
        duplicates = cursor.fetchall()
        
        if duplicates:
            print(f"⚠️ Найдено {len(duplicates)} групп дубликатов")
            print("   Удаляем дубликаты, оставляя только первую запись...")
            
            for dup in duplicates:
                business_id, source, external_review_id, cnt = dup
                # Оставляем первую запись (по created_at), удаляем остальные
                cursor.execute("""
                    DELETE FROM ExternalBusinessReviews
                    WHERE business_id = ? AND source = ? AND external_review_id = ?
                    AND id NOT IN (
                        SELECT id FROM ExternalBusinessReviews
                        WHERE business_id = ? AND source = ? AND external_review_id = ?
                        ORDER BY created_at ASC
                        LIMIT 1
                    )
                """, (business_id, source, external_review_id, business_id, source, external_review_id))
            
            print(f"✅ Удалено дубликатов")
        
        # Создаем уникальный индекс (в SQLite это работает как UNIQUE constraint)
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_ext_reviews_unique
            ON ExternalBusinessReviews(business_id, source, external_review_id)
            WHERE external_review_id IS NOT NULL
        """)
        print("✅ Уникальный индекс создан")
        
        # Также создаем обычный индекс для случаев, когда external_review_id = NULL
        # (UNIQUE не работает с NULL в SQLite, поэтому нужен отдельный индекс)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ext_reviews_business_source
            ON ExternalBusinessReviews(business_id, source)
        """)
        print("✅ Дополнительный индекс создан")
    
    safe_migrate(apply_migration, "add_unique_constraint_external_reviews")

if __name__ == "__main__":
    migrate()
