#!/usr/bin/env python3
"""
Migration: Add is_verified column to MapParseResults table
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

def add_verification_column(cursor):
    """Add is_verified column to MapParseResults table"""
    # Check existing columns first
    cursor.execute("PRAGMA table_info(MapParseResults)")
    columns = {row[1] for row in cursor.fetchall()}
    
    if "is_verified" not in columns:
        try:
            cursor.execute("ALTER TABLE MapParseResults ADD COLUMN is_verified INTEGER DEFAULT 0")
            print("  ✅ Added column: is_verified")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print("  ⏩ Column already exists: is_verified")
            else:
                raise
    else:
        print("  ⏩ Column already exists: is_verified")

if __name__ == "__main__":
    print("🚀 Adding verification column to MapParseResults...")
    safe_migrate(add_verification_column, "Add is_verified column")
    print("✅ Migration completed!")
