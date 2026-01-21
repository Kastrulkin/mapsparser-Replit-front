#!/usr/bin/env python3
"""
Migration: Add business profile completeness fields to MapParseResults
"""
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from safe_db_utils import get_db_connection

def migrate():
    """Add new fields for business profile completeness tracking"""
    print("🔄 Migrating MapParseResults table...")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get current columns
        cursor.execute("PRAGMA table_info(MapParseResults)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        
        # Define new columns to add
        new_columns = [
            ("is_verified", "INTEGER DEFAULT 0", "Verification badge (синяя галочка)"),
            ("phone", "TEXT", "Business phone number"),
            ("website", "TEXT", "Business website"),
            ("messengers", "TEXT", "Messengers JSON (WhatsApp, Telegram, etc.)"),
            ("working_hours", "TEXT", "Working hours JSON"),
            ("services_count", "INTEGER DEFAULT 0", "Number of services/products"),
            ("profile_completeness", "INTEGER DEFAULT 0", "Profile completeness score 0-100%"),
        ]
        
        added_count = 0
        for col_name, col_type, description in new_columns:
            if col_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE MapParseResults ADD COLUMN {col_name} {col_type}")
                    print(f"✅ Added column: {col_name} - {description}")
                    added_count += 1
                except Exception as e:
                    print(f"❌ Error adding {col_name}: {e}")
            else:
                print(f"⏭️  Column {col_name} already exists")
        
        conn.commit()
        
        if added_count > 0:
            print(f"\n✅ Migration completed! Added {added_count} new columns")
        else:
            print("\n✅ No new columns to add - schema is up to date")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
