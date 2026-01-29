
import sqlite3
import os

DB_PATH = "src/reports.db"

def migrate():
    print("🚀 Starting migration: Add 'competitors' to MapParseResults")
    
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(MapParseResults)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "competitors" not in columns:
            print("🔧 Adding 'competitors' column...")
            cursor.execute("ALTER TABLE MapParseResults ADD COLUMN competitors TEXT")
            print("✅ Column added successfully")
        else:
            print("ℹ️ Column 'competitors' already exists")
            
        conn.commit()
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
