import sys
import os
import sqlite3

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from safe_db_utils import get_db_path

def migrate():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print(f"📦 Migrating database: {db_path}")
    
    try:
        # Create ExternalBusinessStats table
        print("Creating table ExternalBusinessStats...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ExternalBusinessStats (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                source TEXT NOT NULL,
                date TEXT NOT NULL,
                views_total INTEGER,
                clicks_total INTEGER,
                actions_total INTEGER,
                rating REAL,
                reviews_total INTEGER,
                raw_payload TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE,
                UNIQUE(business_id, source, date)
            )
        """)
        
        # Create indexes
        print("Creating indexes...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ext_stats_business_id ON ExternalBusinessStats(business_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ext_stats_source ON ExternalBusinessStats(source)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ext_stats_date ON ExternalBusinessStats(date)")
        
        conn.commit()
        print("✅ Table ExternalBusinessStats created successfully.")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
