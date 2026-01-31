#!/usr/bin/env python3
"""
Migration script to add new columns to GrowthTasks table
for Yandex Maps Growth Strategy features.
Includes automatic backup via safe_db_utils.
"""
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.safe_db_utils import safe_migrate

def run_migration(cursor):
    """
    Callback function that performs the actual schema changes.
    """
    print("🔄 Checking GrowthTasks table schema...")
    
    # Get existing columns
    cursor.execute("PRAGMA table_info(GrowthTasks)")
    columns = [row[1] for row in cursor.fetchall()]
    
    # Define new columns
    new_columns = [
        ("check_logic", "TEXT"),
        ("reward_value", "INTEGER DEFAULT 0"),
        ("reward_type", "TEXT DEFAULT 'time_saved'"),
        ("tooltip", "TEXT"),
        ("link_url", "TEXT"),
        ("link_text", "TEXT"),
        ("is_auto_verifiable", "INTEGER DEFAULT 0")
    ]
    
    changes_made = False
    for col_name, col_def in new_columns:
        if col_name not in columns:
            try:
                cursor.execute(f"ALTER TABLE GrowthTasks ADD COLUMN {col_name} {col_def}")
                print(f"✅ Added column: {col_name}")
                changes_made = True
            except Exception as e:
                print(f"⚠️ Failed to add column {col_name}: {e}")
                raise e # Re-raise to trigger rollback in safe_migrate
        else:
            print(f"ℹ️ Column {col_name} already exists")
            
    if not changes_made:
        print("✨ No changes needed")

if __name__ == "__main__":
    print("🚀 Starting safe migration for GrowthTasks...")
    success = safe_migrate(run_migration, description="Add Yandex Growth columns")
    
    if success:
        sys.exit(0)
    else:
        sys.exit(1)
