#!/usr/bin/env python3
"""
Migration: Add missing columns to MapParseResults table
- title: Название организации
- products: Услуги (JSON)
"""
import sqlite3
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from safe_db_utils import safe_migrate, get_db_path
except ImportError:
    # Fallback if safe_db_utils not available
    def get_db_path():
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reports.db')
    
    def safe_migrate(description, migrate_func):
        db_path = get_db_path()
        print(f"📦 Migrating database: {db_path}")
        conn = sqlite3.connect(db_path)
        try:
            migrate_func(conn)
            conn.commit()
            print(f"✅ Migration completed: {description}")
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

def add_missing_columns(cursor):
    """Add missing columns to MapParseResults table"""
    # cursor is passed directly by safe_migrate on server
    
    columns_to_add = [
        ("title", "TEXT"),
        ("products", "TEXT"),
        ("rating", "TEXT"),
        ("reviews_count", "INTEGER"),
        ("address", "TEXT"),
        ("phone", "TEXT"),
        ("website", "TEXT"),
        ("working_hours", "TEXT"),
        ("features", "TEXT"),
        ("photos_count", "INTEGER"),
        ("posts_count", "INTEGER"),
    ]
    
    for col_name, col_type in columns_to_add:
        if col_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE MapParseResults ADD COLUMN {col_name} {col_type}")
                print(f"  ✅ Added column: {col_name}")
            except sqlite3.OperationalError as e:
                if "duplicate column" in str(e).lower():
                    print(f"  ⏩ Column already exists: {col_name}")
                else:
                    raise
        else:
            print(f"  ⏩ Column already exists: {col_name}")

if __name__ == "__main__":
    print("🚀 Adding missing columns to MapParseResults...")
    safe_migrate(add_missing_columns, "Add missing columns to MapParseResults")
    print("✅ Migration completed!")
