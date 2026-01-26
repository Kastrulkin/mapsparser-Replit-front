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
        # Create ExternalBusinessReviews table
        print("Creating table ExternalBusinessReviews...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ExternalBusinessReviews (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                source TEXT NOT NULL,
                external_review_id TEXT,
                rating INTEGER,
                author_name TEXT,
                text TEXT,
                published_at TIMESTAMP,
                response_text TEXT,
                response_at TIMESTAMP,
                raw_payload TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes
        print("Creating indexes...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ext_reviews_business_id ON ExternalBusinessReviews(business_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ext_reviews_source ON ExternalBusinessReviews(source)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ext_reviews_created_at ON ExternalBusinessReviews(created_at)")
        
        conn.commit()
        print("✅ Tables created successfully.")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
