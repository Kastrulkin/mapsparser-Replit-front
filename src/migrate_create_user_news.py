
from safe_db_utils import safe_migrate

def run_migration(cursor):
    """
    Creates UserNews table if missing.
    """
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='UserNews'")
    if not cursor.fetchone():
        print("Creating UserNews table...")
        cursor.execute("""
            CREATE TABLE UserNews (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                service_id TEXT,
                source_text TEXT,
                generated_text TEXT NOT NULL,
                approved INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE,
                FOREIGN KEY (service_id) REFERENCES UserServices(id) ON DELETE SET NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_news_user_id ON UserNews(user_id)")
        print("✅ UserNews created.")
    else:
        # Check for missing updated_at column (backwards compatibility for broken main.py creation)
        cursor.execute("PRAGMA table_info(UserNews)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'updated_at' not in columns:
            print("⚠️ UserNews exists but missing updated_at. Adding it...")
            # SQLite Limitation: Cannot add column with non-constant default (CURRENT_TIMESTAMP) in some versions
            try:
                cursor.execute("ALTER TABLE UserNews ADD COLUMN updated_at TIMESTAMP")
                cursor.execute("UPDATE UserNews SET updated_at = created_at WHERE updated_at IS NULL")
                print("✅ Added updated_at to UserNews (backfilled from created_at).")
            except Exception as e:
                print(f"⚠️ Failed to add updated_at: {e}")
                raise e
        else:
            print("✨ UserNews already exists and is correct.")

def migrate():
    print("🚀 Starting safe migration for UserNews...")
    success = safe_migrate(run_migration, "Create UserNews table")
    
    if success:
        print("✅ Migration completed successfully!")
    else:
        print("❌ Migration failed!")
        exit(1)

if __name__ == "__main__":
    migrate()
