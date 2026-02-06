#!/usr/bin/env python3
"""
Migration: Add business profile completeness fields to MapParseResults
"""
import sys
import os
import shutil
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from safe_db_utils import get_db_connection, get_db_path

def create_backup():
    """Create backup of database before migration"""
    db_path = get_db_path()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{db_path}.backup_{timestamp}"
    
    print("📦 Creating database backup...")
    print(f"   Source: {db_path}")
    print(f"   Backup: {backup_path}")
    
    try:
        shutil.copy2(db_path, backup_path)
        backup_size = os.path.getsize(backup_path) / (1024 * 1024)  # MB
        print(f"✅ Backup created successfully ({backup_size:.2f} MB)")
        return backup_path
    except Exception as e:
        print(f"❌ Failed to create backup: {e}")
        print("⚠️  MIGRATION ABORTED - Cannot proceed without backup!")
        return None

def migrate():
    """Add new fields for business profile completeness tracking"""
    print("🔄 Starting MapParseResults migration...")
    print()
    
    # CRITICAL: Create backup first
    backup_path = create_backup()
    if not backup_path:
        return False
    
    print()
    print("🔄 Applying schema changes...")
    
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
        
        print()
        print("=" * 60)
        if added_count > 0:
            print(f"✅ Migration completed! Added {added_count} new columns")
        else:
            print("✅ No new columns to add - schema is up to date")
        print()
        print("💾 Database backup saved to:")
        print(f"   {backup_path}")
        print("   (Keep this backup until you verify the migration worked)")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print()
        print("=" * 60)
        print(f"❌ Migration failed: {e}")
        print()
        print("🔄 To restore from backup:")
        print(f"   cp {backup_path} {get_db_path()}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
