
import sqlite3
import os
import sys

# Add parent directory to path to import safe_db_utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from safe_db_utils import get_db_connection
except ImportError:
    # Fallback if safe_db_utils is not found or path is wrong
    def get_db_connection():
        return sqlite3.connect('reports.db')

def migrate():
    print("Running migration: Adding ProspectingLeads table...")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Create ProspectingLeads table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ProspectingLeads (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                address TEXT,
                phone TEXT,
                website TEXT,
                rating REAL,
                reviews_count INTEGER,
                source_url TEXT,
                google_id TEXT,
                category TEXT,
                location TEXT,
                status TEXT DEFAULT 'new',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Check if table created successfully
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ProspectingLeads'")
        if cursor.fetchone():
            print("✅ Table ProspectingLeads created successfully")
        else:
            print("❌ Failed to create table ProspectingLeads")
            
        conn.commit()
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
