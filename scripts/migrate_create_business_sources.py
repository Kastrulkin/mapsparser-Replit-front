import os
import sys
import psycopg2
from psycopg2 import sql

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from database_manager import DatabaseManager

def migrate_business_sources():
    print("🚀 Starting migration: Creating business_sources table...")
    
    db = DatabaseManager()
    conn = db.conn
    cursor = conn.cursor()

    try:
        # 1. Create table
        print("Creating table `business_sources`...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS business_sources (
                id SERIAL PRIMARY KEY,
                business_id TEXT NOT NULL REFERENCES Businesses(id) ON DELETE CASCADE,
                source VARCHAR(50) NOT NULL, -- 'yandex', 'google', '2gis'
                external_id VARCHAR(255),    -- yandex_org_id
                url TEXT,                    -- yandex_url
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_business_source UNIQUE (business_id, source)
            );
        """)
        
        # Add index on external_id for fast lookup during parsing
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_business_sources_external_id ON business_sources(external_id);
        """)
        print("✅ Table created.")

        # 2. Migrate existing data from Businesses
        print("Migrating data from `Businesses` (yandex_url, yandex_org_id)...")
        
        # Select existing data
        cursor.execute("""
            SELECT id, yandex_url, yandex_org_id 
            FROM Businesses 
            WHERE yandex_url IS NOT NULL OR yandex_org_id IS NOT NULL;
        """)
        rows = cursor.fetchall()
        print(f"Found {len(rows)} businesses to migrate.")
        
        migrated_count = 0
        for row in rows:
            b_id, url, org_id = row
            
            # Check if already exists to avoid bad duplicates if script re-runs
            cursor.execute("""
                INSERT INTO business_sources (business_id, source, external_id, url)
                VALUES (?, 'yandex', ?, ?)
                ON CONFLICT (business_id, source) 
                DO UPDATE SET 
                    external_id = EXCLUDED.external_id,
                    url = EXCLUDED.url,
                    updated_at = CURRENT_TIMESTAMP;
            """, (b_id, org_id, url))
            migrated_count += 1
            
        print(f"✅ Migrated {migrated_count} records to `business_sources`.")

        conn.commit()
        print("\n🎉 Migration `business_sources` completed successfully!")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    migrate_business_sources()
