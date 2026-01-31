#!/usr/bin/env python3
"""
Migration script to create ExternalBusinessAccounts table
which stores credentials for external services (Yandex.Business, 2GIS, etc.)
"""
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.safe_db_utils import safe_migrate

def run_migration(cursor):
    """
    Creates ExternalBusinessAccounts table
    """
    print("🔄 Checking ExternalBusinessAccounts table...")
    
    # Check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ExternalBusinessAccounts'")
    if cursor.fetchone():
        print("ℹ️ Table ExternalBusinessAccounts already exists.")
        
        # Check for auth_data_encrypted column
        cursor.execute("PRAGMA table_info(ExternalBusinessAccounts)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'auth_data_encrypted' not in columns:
             print("⚠️ Column auth_data_encrypted missing. Dropping table to recreate with correct schema...")
             cursor.execute("DROP TABLE ExternalBusinessAccounts")
        else:
             print("✅ Schema is correct.")
             return

    print("🛠 Creating ExternalBusinessAccounts table...")
    cursor.execute("""
        CREATE TABLE ExternalBusinessAccounts (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            source TEXT NOT NULL, -- 'yandex_business', '2gis', 'google_business'
            external_id TEXT, -- ID inside the external system (e.g. org_id)
            display_name TEXT,
            auth_data_encrypted TEXT, -- JSON with cookies, tokens, etc. (encrypted or plain)
            is_active INTEGER DEFAULT 1,
            last_sync_at TIMESTAMP,
            last_error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE,
            UNIQUE(business_id, source)
        )
    """)
    print("✅ Table ExternalBusinessAccounts created successfully")
    
    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ext_accounts_business_id ON ExternalBusinessAccounts(business_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ext_accounts_source ON ExternalBusinessAccounts(source)")
    print("✅ Indexes created")

if __name__ == "__main__":
    print("🚀 Starting migration for ExternalBusinessAccounts...")
    success = safe_migrate(run_migration, description="Create ExternalBusinessAccounts table")
    
    if success:
        print("🎉 Migration completed successfully!")
        sys.exit(0)
    else:
        print("❌ Migration failed!")
        sys.exit(1)
