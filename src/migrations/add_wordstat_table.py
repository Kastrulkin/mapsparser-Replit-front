import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from safe_db_utils import get_db_connection

def migrate():
    print("🔄 Running migration: add_wordstat_table...")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Create WordstatKeywords table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS WordstatKeywords (
                id TEXT PRIMARY KEY,
                keyword TEXT UNIQUE NOT NULL,
                views INTEGER DEFAULT 0,
                category TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indices
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wordstat_views ON WordstatKeywords(views DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wordstat_category ON WordstatKeywords(category)")
        
        conn.commit()
        print("✅ WordstatKeywords table created successfully")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
