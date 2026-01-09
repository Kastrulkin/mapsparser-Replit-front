import sqlite3
import sys
import os

# Add src to path to import safe_db_utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from safe_db_utils import safe_migrate

def create_growth_tables(cursor):
    print("Creating BusinessTypes table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS BusinessTypes (
            id TEXT PRIMARY KEY,
            type_key TEXT UNIQUE NOT NULL,
            label TEXT NOT NULL,
            description TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    print("Creating GrowthStages table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS GrowthStages (
            id TEXT PRIMARY KEY,
            business_type_id TEXT NOT NULL,
            stage_number INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            goal TEXT,
            expected_result TEXT,
            duration TEXT,
            is_permanent INTEGER DEFAULT 0,
            tasks TEXT, -- JSON array of strings
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (business_type_id) REFERENCES BusinessTypes(id) ON DELETE CASCADE
        )
    """)
    
    print("Creating BusinessOptimizationWizard table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS BusinessOptimizationWizard (
            business_id TEXT PRIMARY KEY,
            step INTEGER DEFAULT 1,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE CASCADE
        )
    """)

if __name__ == "__main__":
    print("Starting migration...")
    success = safe_migrate(create_growth_tables, "Create Growth Stages Tables")
    if success:
        print("Migration successful")
    else:
        print("Migration failed")
        sys.exit(1)
