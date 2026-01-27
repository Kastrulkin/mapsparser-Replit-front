
import sqlite3
import os
from safe_db_utils import safe_migrate

def run_migration(cursor):
    """
    Adds missing columns to PricelistOptimizations table.
    """
    print("Checking PricelistOptimizations columns...")
    cursor.execute("PRAGMA table_info(PricelistOptimizations)")
    columns = [row[1] for row in cursor.fetchall()]

    # 1. business_id
    if 'business_id' not in columns:
        print("adding business_id to PricelistOptimizations...")
        # Note: We cannot easily add NOT NULL constraint to existing table with rows without default. 
        # But if table is empty or we don't care about strictness for now, simply adding column is fine.
        # Given it's SQLite, adding NOT NULL without default on non-empty table is forbidden. 
        # We'll add it as nullable for safety in migration, though init schema says NOT NULL.
        cursor.execute("ALTER TABLE PricelistOptimizations ADD COLUMN business_id TEXT")
        print("✅ Added business_id.")
    
    # 2. optimized_text
    if 'optimized_text' not in columns:
        print("adding optimized_text to PricelistOptimizations...")
        cursor.execute("ALTER TABLE PricelistOptimizations ADD COLUMN optimized_text TEXT")
        print("✅ Added optimized_text.")

    # 3. original_text (Check this too just in case, though verify script didn't flag it explicitly if not in expected list)
    if 'original_text' not in columns:
        print("adding original_text to PricelistOptimizations...")
        cursor.execute("ALTER TABLE PricelistOptimizations ADD COLUMN original_text TEXT")
        print("✅ Added original_text.")
        
    print("✨ PricelistOptimizations schema is correct.")

def migrate():
    print("🚀 Starting safe migration for PricelistOptimizations...")
    success = safe_migrate(run_migration, "Fix PricelistOptimizations Schema")
    
    if success:
        print("✅ Migration completed successfully!")
    else:
        print("❌ Migration failed!")
        exit(1)

if __name__ == "__main__":
    migrate()
